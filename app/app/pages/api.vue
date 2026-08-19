<script setup lang="ts">
const { t } = useI18n()

// Whether this backend serves an MCP endpoint at all: it lives behind the optional `[mcp]` extra,
// so an instance installed without it has no /mcp route and must not be told to point a client at
// one. The backend reports it next to its version, which is the only thing the card waits for.
// `$fetch` rather than `useFetch`: the answer is a fact about the backend, not page state, and
// `useFetch` would key it by URL and hand back whatever the app shell already cached for
// /api/version -- which is the version, fetched before this page existed.
const backend = await $fetch<{ version: string, mcp_enabled?: boolean }>('/api/version').catch(() => null)
const mcpEnabled = computed(() => backend?.mcp_enabled === true)

// The MCP endpoint is served on this app's own origin: the app proxies /mcp through to the
// backend, preserving the streamable-HTTP transport. Reading the origin rather than hard-coding
// the public URL means the snippet is also correct on a self-hosted or local instance.
const mcpUrl = computed(() => `${useRequestURL().origin}/mcp`)
const mcpClientConfig = computed(() => JSON.stringify(
  { mcpServers: { wetterdienst: { url: mcpUrl.value } } },
  null,
  2,
))

const endpoints = [
  { name: 'coverage', path: '/api/coverage', descKey: 'api.endpoints.coverage' },
  { name: 'stations', path: '/api/stations', descKey: 'api.endpoints.stations' },
  { name: 'history', path: '/api/history', descKey: 'api.endpoints.history' },
  { name: 'values', path: '/api/values', descKey: 'api.endpoints.values' },
  { name: 'interpolate', path: '/api/interpolate', descKey: 'api.endpoints.interpolate' },
  { name: 'summarize', path: '/api/summarize', descKey: 'api.endpoints.summarize' },
  { name: 'stripes/stations', path: '/api/stripes/stations', descKey: 'api.endpoints.stripesStations' },
  { name: 'stripes/values', path: '/api/stripes/values', descKey: 'api.endpoints.stripesValues' },
  { name: 'stripes/image', path: '/api/stripes/image', descKey: 'api.endpoints.stripesImage' },
]

const examples = [
  { nameKey: 'api.examples.stationsDwd', path: '/api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true' },
  { nameKey: 'api.examples.historyDwd', path: '/api/history?provider=dwd&network=observation&parameters=daily/kl&station=00011' },
  { nameKey: 'api.examples.valuesDwd', path: '/api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&station=00011' },
  { nameKey: 'api.examples.interpolateDwd', path: '/api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01' },
  { nameKey: 'api.examples.summarizeDwd', path: '/api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01' },
  { nameKey: 'api.examples.stripesStations', path: '/api/stripes/stations?kind=temperature' },
  { nameKey: 'api.examples.stripesValues', path: '/api/stripes/values?kind=temperature&station=1048' },
  { nameKey: 'api.examples.stripesImage', path: '/api/stripes/image?kind=temperature&station=1048' },
]
</script>

<template>
  <UContainer class="mx-auto max-w-3xl px-4 py-6 space-y-6">
    <div class="text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">
        {{ t('api.title') }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ t('api.subtitle') }}
      </p>
    </div>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-code-2" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('api.endpointsTitle') }}
          </h2>
        </div>
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
          <span class="text-sm text-gray-600 dark:text-gray-400 pt-1">{{ t(endpoint.descKey) }}</span>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-terminal" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('api.examplesTitle') }}
          </h2>
        </div>
      </template>
      <div class="space-y-2">
        <div v-for="example in examples" :key="example.nameKey">
          <UButton
            :to="example.path"
            target="_blank"
            size="sm"
            variant="link"
            class="text-left"
          >
            {{ t(example.nameKey) }}
          </UButton>
        </div>
      </div>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-file-json" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('api.formatsTitle') }}
          </h2>
        </div>
      </template>
      <i18n-t keypath="api.formatsText" tag="p" class="text-gray-600 dark:text-gray-400 mb-4" scope="global">
        <template #format>
          <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">format</code>
        </template>
      </i18n-t>
      <ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400">
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">json</code> - {{ t('api.formatJson') }}</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">csv</code> - {{ t('api.formatCsv') }}</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">geojson</code> - {{ t('api.formatGeojson') }}</li>
        <li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">html</code> - {{ t('api.formatHtml') }}</li>
      </ul>
    </UCard>

    <UCard v-if="mcpEnabled">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bot" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('api.mcpTitle') }}
          </h2>
        </div>
      </template>
      <p class="text-gray-600 dark:text-gray-400 mb-4">
        {{ t('api.mcpText') }}
      </p>
      <p class="text-gray-600 dark:text-gray-400 mb-2">
        {{ t('api.mcpUrlLabel') }}
      </p>
      <pre class="bg-gray-100 dark:bg-gray-800 rounded p-3 mb-4 overflow-x-auto text-sm"><code>{{ mcpUrl }}</code></pre>
      <p class="text-gray-600 dark:text-gray-400 mb-2">
        {{ t('api.mcpClientLabel') }}
      </p>
      <pre class="bg-gray-100 dark:bg-gray-800 rounded p-3 mb-4 overflow-x-auto text-sm"><code>{{ mcpClientConfig }}</code></pre>
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{ t('api.mcpNoAuth') }}
      </p>
      <UButton
        to="https://wetterdienst.readthedocs.io/en/latest/usage/restapi.html#mcp-endpoint"
        target="_blank"
        size="sm"
        variant="link"
        icon="i-lucide-book-open"
        class="px-0"
      >
        {{ t('api.mcpDocs') }}
      </UButton>
    </UCard>

    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-list" class="text-primary-500 shrink-0" />
          <h2 class="text-lg font-bold">
            {{ t('api.commonParamsTitle') }}
          </h2>
        </div>
      </template>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b dark:border-gray-700">
              <th class="text-left py-2 pr-4">
                {{ t('api.paramHeader') }}
              </th>
              <th class="text-left py-2">
                {{ t('api.descHeader') }}
              </th>
            </tr>
          </thead>
          <tbody class="text-gray-600 dark:text-gray-400">
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">provider</code>
              </td>
              <td class="py-2">
                {{ t('api.params.provider') }}
              </td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">network</code>
              </td>
              <td class="py-2">
                {{ t('api.params.network') }}
              </td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">parameters</code>
              </td>
              <td class="py-2">
                {{ t('api.params.parameters') }}
              </td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">station</code>
              </td>
              <td class="py-2">
                {{ t('api.params.station') }}
              </td>
            </tr>
            <tr class="border-b dark:border-gray-700">
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">date</code>
              </td>
              <td class="py-2">
                {{ t('api.params.date') }}
              </td>
            </tr>
            <tr>
              <td class="py-2 pr-4">
                <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">format</code>
              </td>
              <td class="py-2">
                {{ t('api.params.format') }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </UContainer>
</template>
