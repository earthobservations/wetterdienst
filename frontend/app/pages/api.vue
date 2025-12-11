<script setup lang="ts">
const endpoints = [
  { name: 'coverage', path: '/api/coverage', description: 'Discover available providers, networks, resolutions, and parameters' },
  { name: 'stations', path: '/api/stations', description: 'Query weather stations by various filters' },
  { name: 'values', path: '/api/values', description: 'Retrieve observation values for selected stations and parameters' },
  { name: 'interpolate', path: '/api/interpolate', description: 'Interpolate values for a specific location' },
  { name: 'summarize', path: '/api/summarize', description: 'Get summarized values for a location' },
  { name: 'stripes/stations', path: '/api/stripes/stations', description: 'Get stations for climate stripes visualization' },
  { name: 'stripes/values', path: '/api/stripes/values', description: 'Generate climate stripes visualization' },
]

const examples = [
  { name: 'DWD Observation Daily Climate Stations', path: '/api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true' },
  { name: 'DWD Observation Daily Climate Values', path: '/api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&station=00011' },
  { name: 'DWD Observation Daily Climate Interpolation', path: '/api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01' },
  { name: 'DWD Observation Daily Climate Summary', path: '/api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01' },
  { name: 'Climate Stripes Stations (Temperature)', path: '/api/stripes/stations?kind=temperature' },
  { name: 'Climate Stripes Values (Temperature)', path: '/api/stripes/values?kind=temperature&station=1048' },
]
</script>
<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div class="text-center mb-12">
      <h1 class="text-4xl font-bold mb-4">REST API</h1>
      <p class="text-xl text-gray-600 dark:text-gray-400">
        Access weather data programmatically
      </p>
    </div>

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">Endpoints</h2>
      </template>
      <div class="space-y-3">
        <div v-for="endpoint in endpoints" :key="endpoint.name" class="flex items-start gap-3">
          <UButton
            :to="endpoint.path"
            target="_blank"
            size="sm"
            variant="outline"
            class="font-mono shrink-0"
          >
            {{ endpoint.name }}
          </UButton>
          <span class="text-sm text-gray-600 dark:text-gray-400 pt-1">{{ endpoint.description }}</span>
        </div>
      </div>
    </UCard>

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">Examples</h2>
      </template>
      <div class="space-y-2">
        <div v-for="example in examples" :key="example.name">
          <UButton
            :to="example.path"
            target="_blank"
            size="sm"
            variant="link"
            class="text-left"
          >
            {{ example.name }}
          </UButton>
        </div>
      </div>
    </UCard>

    <UCard class="mb-8">
      <template #header>
        <h2 class="text-lg font-semibold">Response Formats</h2>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        All endpoints support multiple output formats via the <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">format</code> query parameter:
      </p>
      <ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400">
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">json</code> - JSON format (default)</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">csv</code> - CSV format</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">geojson</code> - GeoJSON format for mapping</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">html</code> - HTML table format</li>
      </ul>
    </UCard>

    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">Common Parameters</h2>
      </template>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b dark:border-gray-700">
              <th class="text-left py-2 pr-4">Parameter</th>
              <th class="text-left py-2">Description</th>
            </tr>
          </thead>
          <tbody class="text-gray-600 dark:text-gray-400">
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">provider</code></td>
              <td class="py-2">Data provider (e.g., dwd, noaa)</td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">network</code></td>
              <td class="py-2">Data network (e.g., observation, forecast)</td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">parameters</code></td>
              <td class="py-2">Parameter path (e.g., daily/kl/temperature_air_mean_2m)</td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">station</code></td>
              <td class="py-2">Station ID(s), comma-separated</td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">date</code></td>
              <td class="py-2">Date or date range (e.g., 2020-01-01/2020-12-31)</td>
            </tr>
            <tr>
              <td class="py-2 pr-4"><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">format</code></td>
              <td class="py-2">Output format (json, csv, geojson, html)</td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </div>
</template>